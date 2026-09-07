"""Real media regression: preserve source pixels until MotionContext resizes them."""
import tempfile
import unittest
import wave
from pathlib import Path
from PIL import Image
from h3ui.video_assembly import media


class TailGeometryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source.mp4'
        media.command(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','color=c=red:s=1248x704:r=24:d=2',
                       '-c:v','libx264','-pix_fmt','yuv420p',self.source])

    def frame(self,video):
        file=self.root/'frame.png'
        media.command(['ffmpeg','-nostdin','-y','-v','error','-i',video,'-frames:v','1',file])
        with Image.open(file) as image:return image.convert('RGB')

    def test_tail_keeps_full_frame_without_new_black_borders(self):
        before=media.digest(self.source)
        for width,height in [(832,480),(416,736)]:
            context=media.tail(self.source,0,2,self.root/f'tail-{width}',width,height,self.root)
            video=self.root/context['video'];image=self.frame(video)
            self.assertEqual(image.size,(1248,704),'canvas alignment must be left to the existing MotionContext node')
            for x,y in [(0,0),(1247,0),(0,703),(1247,703),(624,0)]:
                self.assertGreater(image.getpixel((x,y))[0],230,'new black border in prepared tail')
            count=media.command(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=nb_read_frames','-of','csv=p=0',video])
            self.assertEqual(int(count.strip()),22)
            with wave.open(str(self.root/context['audio'])) as audio:self.assertEqual(audio.getnframes(),32000)
        self.assertEqual(media.digest(self.source),before)

    def test_export_and_old_submission_keep_their_explicit_padding_policy(self):
        old=media.tail(self.source,0,2,self.root/'old',832,480,self.root,preparation='legacy_contain_v1')
        image=self.frame(self.root/old['video'])
        self.assertEqual(image.size,(832,480));self.assertLess(max(image.getpixel((416,0))),20)
        output=self.root/'export.mkv'
        media.normalize(self.source,output,0,1,832,480,fit='contain')
        image=self.frame(output);self.assertLess(max(image.getpixel((416,0))),20)
        with self.assertRaisesRegex(ValueError,'未知片尾准备版本'):
            media.tail(self.source,0,2,self.root/'unknown',832,480,self.root,preparation='unknown')


if __name__=='__main__':unittest.main()
